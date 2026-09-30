---
id: 23398
severity: "High"
---

# Math512Lib sqrt512 and div512by256 Vulnerability

## Description

Description: Math512Lib::sqrt512 implements a full-width integer Newton-Raphson square root. This hinges on the assumption that the initial guess is larger than the upper limb and fits within 256 bits such that the iteration is strictly monotonically decreasing, i.e. converges on the true square root. However, when the most significant bit of the upper limb is odd, floor division by two can result in an initial guess that is smaller than the upper limb, causing the quotient of floor(([x1 x0]) / root) >= 2ˆ256 to be too wide.

```solidity
function sqrt512(uint256 x1, uint256 x0) internal pure returns (uint256 root) {
    if (x1 == 0) {
        return FixedPointMathLib.sqrt(x0);
    }
    @> root = 1 << (128 + (LibBit.fls(x1) / 2));
    uint256 last;
    do {
        last = root;
        // Because !floor(sqrt(UINT512_MAX)) = 2^256-1! and guesses converging towards the
        // correct result the result of all divisions is guaranteed to fit within 256 bits.
        @> (, root) = div512by256(x1, x0, root);
        root = (root + last) / 2;
    } while (root != last);
    return root;
}
```

The high digit returned by Math512Lib::div512by256 is correctly ignored per the intended implementation details, although this also depends on the assumption that the initial guess fits within 256 bits which can be violated as demonstrated.

Furthermore, the implementation of Math512Lib::div512by256 is such that the long division should be equivalent to the Solady implementation from which it was adapted. This is not the case, as the synthesis of in calculating the remainder with the upper limb in place of r1 is incorrect:

```solidity
/// @dev Computes ![x1 x0] / d!
function div512by256(uint256 x1, uint256 x0, uint256 d)
    internal
    pure
    returns (uint256 y1, uint256 y0)
{
    if (d == 0) revert DivisorZero();
    assembly {
        // Compute first "digit" of long division result
        y1 := div(x1, d)
        // We take the remainder to continue the long division
        let r1 := mod(x1, d)
        // We complete the long division by computing !y0 = [r1 x0] / d!. We use the "512 by
        // 256 division" logic from Solady's !fullMulDiv! (Credit under MIT license:
        // https://github.com/Vectorized/solady/blob/main/src/utils/FixedPointMathLib.sol)
        // We need to compute ![r1 x0] mod d = r1 * 2^256 + x0 = (r1 * 2^128) * 2^128 + x0!.
        @> let r := addmod(mulmod(shl(128, x1), shl(128, 1), d), x0, d)
        // Same math from Solady, reference !fullMulDiv! for explanation.
        let t := and(d, sub(0, d))
        d := div(d, t)
        let inv := xor(2, mul(3, d)) // inverse mod 2**4
        inv := mul(inv, sub(2, mul(d, inv))) // inverse mod 2**8
        inv := mul(inv, sub(2, mul(d, inv))) // inverse mod 2**16
        inv := mul(inv, sub(2, mul(d, inv))) // inverse mod 2**32
        inv := mul(inv, sub(2, mul(d, inv))) // inverse mod 2**64
        inv := mul(inv, sub(2, mul(d, inv))) // inverse mod 2**128
        10
        // Edits vs Solady: !x0! replaces !z!, !r1! replaces !p1!, final 256-bit result stored in !y0!
        y0 :=
            mul(
                @> or(mul(sub(r1, gt(r, x0)), add(div(sub(0, t), t), 1)), div(sub(x0, r), t)),
                mul(sub(2, mul(d, inv)), inv) // inverse mod 2**256
            )
    }
}
```

Rather than forming the desired computation, the left shift construction truncates the top 128 bits before the modulo step. The magnitude of these dropped high bits determines whether r and hence y0 is biased upward or downward by application of the borrow step.

Combined, these issues have serious implications for the overall computation of the effective price:
- Every invocation of Math512Lib::div512by256 in CompensationPriceFinder asserts that the upper bits are zero. This holds true so long as x1 < d, i.e. the upper bits of L +/- sqrt(D) are less than A = Xhat + x - B such that the solution fits within 256 bits. Thus, the upper 128 bits of L + sqrt(D), can be used to influence the calculated compensation price. This is dependent entirely on the liquidity distribution, so by extension the lower/upper tick prices, range reserves, and delta sums. However, note that this can also be influenced by incorrect application of the square root when computing sqrt(D).
- The invocation of Math512Lib::div512by256 in Math512Lib::sqrt512 ignores the upper limb, so it is the upper 128 bits of the input upper limb that influence the resulting root calculation, along with the bug in Math512Lib::sqrt512 itself. If the last set bit is even, then the returned root can deviate around the true root, since the Math512Lib::sqrt512 implementation will converge on the true root but the Math512Lib::div512by256 implementation will incorrectly apply the borrow step. If the last set bit is odd, then the returned root will be significantly smaller than the true root, and again this can deviate in both directions depending on the upper 128 bits of the upper limb.
- CompensationPriceFinder::getZeroForOne and CompensationPriceFinder::getOneForZero both pass the full precision multiplication of simplePstarX96 with 2**96 which requires at most 353 bits (i.e. empty upper 128 bits of the upper limb). Therefore, these invocations of Math512Lib::sqrt512 should only be affected if the last set bit is odd.
- In CompensationPriceFinder::_zeroForOneGetFinalCompensationPrice, the numerator -L + sqrt(D) will be computed incorrectly if the last set bit of D * 2ˆ192 is odd. Again, this is entirely dependent on the liquidity distribution and will result in a smaller numerator than expected (assuming underflow is avoided). Execution then continues to Math512Lib::div512by256 which could return a lower compensation price than expected. Similar is true of the negative A branch, except the numerator and resulting compensation price would be larger than expected.
- In CompensationPriceFinder::_oneForZeroGetFinalCompensationPrice, the numerator L + sqrt(D) will be computed incorrectly in a manner similar to the above, resulting in a smaller numerator and compensation price.

Impact: Math512Lib::sqrt512 is not strictly monotonically decreasing and Math512Lib::div512by256 incorrectly computes long division. This can result in the effective price calculations being incorrect.

## Proof of Concept

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;
import {console, Test} from "forge-std/Test.sol";
import {stdError} from "forge-std/StdError.sol";
import {LibBit} from "solady/src/utils/LibBit.sol";
import {FixedPointMathLib} from "solady/src/utils/FixedPointMathLib.sol";
import {Math512Lib} from "../../src/libraries/Math512Lib.sol";

contract Math512LibHarness {
    using Math512Lib for uint256;

    function fullMul(uint256 x, uint256 y) public pure returns (uint256 z1, uint256 z0) {
        return Math512Lib.fullMul(x, y);
    }

    function sqrt512(uint256 x1, uint256 x0) public pure returns (uint256) {
        return Math512Lib.sqrt512(x1, x0);
    }

    function div512by256(uint256 x1, uint256 x0, uint256 d) public pure returns (uint256 y1, uint256 y0) {
        return Math512Lib.div512by256(x1, x0, d);
    }
}

contract Math512LibTest is Math512LibHarness, Test {
    // BUG: when msb is odd in [129, 245], the quotient is too wide
    function test_oddMsbInitialRootArithmeticError(uint8 msb) public {
        uint256 x0;
        // Choose a msb that is odd and in [129, 245] such that LibBit.fls(x1) returns an odd index
        msb = uint8(129 + 2 * bound(msb, 0, (245 - 129) / 2));
        uint256 x1 = uint256(1) << msb;
        uint256 p = LibBit.fls(x1);
        assertEq(p, msb, "index not equal to msb");
        assertEq(p % 2, 1, "index not odd");
        // Rounds down when p is odd, so we have r0 = 2^(128 + 64) = 2^193
        uint256 r0 = uint256(1) << (128 + (p / 2));
        // If root <= x1, then floor(([x1 x0]) / root) >= 2^256, i.e. quotient too wide.
        if (r0 <= x1) console.log("initial root <= x1 when msb is odd -> unsafe: quotient too wide");
        vm.expectRevert(stdError.arithmeticError);
        uint256 root = this.sqrt512(x1, x0);
    }

    // BUG: when msb is odd in [247, 255], initial root computation overflows
    function test_oddMsbInitialRootOverflow(uint8 msb) public {
        uint256 x0;
        // ensure msb is odd and in [247, 255]
        msb = uint8(247 + 2 * bound(msb, 0, (255 - 247) / 2));
        uint256 x1 = uint256(1) << msb;
        uint256 r0 = uint256(1) << (128 + (LibBit.fls(x1) / 2));
        if (msb != 255) assertGt(r0, x1, "initial root not > x1");
        vm.expectRevert("DivisorZero()");
        uint256 root = this.sqrt512(x1, x0);
    }

    // BUG: when msb is 254 (max even < 256), initial root computation overflows
    function test_evenMsbInitialRootOverflow() public {
        uint256 x0;
        uint8 msb = 254; // max even < 256
        uint256 x1 = uint256(1) << msb;
        uint256 r0 = uint256(1) << (128 + (LibBit.fls(x1) / 2));
        assertGt(r0, x1, "initial root not > x1");
        vm.expectRevert(stdError.arithmeticError);
        uint256 root = this.sqrt512(x1, x0);
    }

    // NOTE: when msb is even in [0, 254), initial root computation is safe
    function test_evenMsbInitialRoot(uint8 msb) public {
        uint256 x0;
        vm.assume(msb % 2 == 0 && msb < 254);
        uint256 x1 = uint256(1) << msb;
        uint256 r0 = uint256(1) << (128 + (LibBit.fls(x1) / 2));
        assertGt(r0, x1, "initial root not > x1");
        uint256 root = this.sqrt512(x1, x0);
    }

    // BUG: when x1 <= d, the quotient fits in 256 bits and y1 should be zero; however,
    // there are cases in which the high digit is not zero, so it should not be ignored
    function test_discardHighDigit(uint256 x0, uint256 x1, uint256 d) public {
        // Only allow inputs that should result in a y1 of 0 (i.e. quotient fits in 256 bits)
        vm.assume(d != 0 && x1 <= d);
        (uint256 y1, ) = this.div512by256(x1, x0, d);
        assertEq(y1, 0, "y1 not zero -> quotient too wide");
    }

    // BUG: when x1 <= d, the quotient fits in 256 bits and y1 should be zero; however,
    // there are cases in which y0 does not collapse to FixedPointMathLib.fullMulDiv(r1, x0, d)
    function test_fullMulDivEquivalence(uint256 x0, uint256 x1, uint256 d) public {
        // Compute 512-bit product
        (uint256 p1, uint256 p0) = this.fullMul(x1, x0);
        // Ensure the high digit does not exceed d; otherwise, the quotient does not fit in 256 bits
        vm.assume(d != 0 && p1 <= d);
        (uint256 y1, uint256 y0) = this.div512by256(p1, p0, d);
        uint256 z = FixedPointMathLib.fullMulDiv(x1, x0, d);
        assertEq(y1, 0, "y1 not zero -> quotient too wide");
        assertEq(y0, z, "y0 not equal to z -> incorrect quotient");
    }
}
```

## Recommendation

Recommended Mitigation: Ensure that the initial square root guess is always larger than the upper limb such that the iteration is monotonically decreasing.

Compute the long division remainder as:

```solidity
let r := addmod(addmod(mulmod(r1, not(0), d), r1, d), x0, d)
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the Math512Lib library, specifically in the sqrt512 function and the div512by256 routine that together compute high‑precision square roots and 512‑by‑256 division used by the protocol’s price‑finding logic. sqrt512 assumes that the initial guess for the square root, derived from a left‑shift based on the index of the most‑significant set bit of the upper 256‑bit limb (x1), is always larger than that limb and fits within 256 bits. When the most‑significant bit index is odd, the shift rounds down, producing a guess that can be smaller than x1. This causes the subsequent division floor(([x1 x0]) / root) to generate a quotient that does not fit in 256 bits (≥ 2^256), leading to an arithmetic overflow or an incorrect root that is significantly smaller than the true value. The Newton‑Raphson iteration therefore does not remain strictly monotonically decreasing and may converge to a wrong result.
In parallel, div512by256 attempts to emulate Solady’s 512‑by‑256 division but incorrectly builds the remainder. The assembly code truncates the high 128 bits of the combined remainder before applying addmod, using a shifted version of x1 instead of the actual remainder r1. This truncation changes the value of r, causing the low digit y0 to be biased upward or downward and allowing the high digit y1 to be non‑zero when the mathematical expectation is zero (i.e., when the dividend fits in 256 bits). Consequently, the long‑division invariant is broken and the computed quotient can be too wide.
Both bugs manifest only under specific edge conditions: an odd most‑significant bit in the upper limb for sqrt512, and inputs where the upper 256‑bit part of the dividend is less than or equal to the divisor for div512by256. These conditions are tied to the protocol’s liquidity distribution because the values fed into the library (L ± sqrt(D) and related terms) depend on reserve balances and tick ranges. An attacker could influence the liquidity layout to create the offending bit pattern, causing the effective price calculation to deviate. Users experience the impact as incorrect compensation or pricing – for example, a trade that should yield a certain amount of tokens may result in a smaller payout, or a compensation claim may return less than the rightful amount, appearing as a missing or zero balance.
The issue was discovered through extensive fuzz testing and targeted unit tests that varied the most‑significant bit of the upper limb, revealing arithmetic reverts and mismatched division results. It is hard to notice in normal operation because the bug only triggers on rare bit patterns; the contract does not revert in many cases but silently returns a wrong price, making the symptom subtle.
To remediate, the initial square‑root guess must be forced to be larger than the upper limb, for instance by adjusting the shift when the bit index is odd or by adding a safety margin. The division routine must be corrected to compute the remainder using the full 256‑bit high part, as shown in the recommended addmod expression that includes both r1 and the full 256‑bit mask. These conceptual fixes restore monotonic convergence of sqrt512 and accurate long‑division in div512by256, eliminating the price‑calculation errors and protecting users from incorrect compensation.
