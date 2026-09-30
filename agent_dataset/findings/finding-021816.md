---
id: 21816
severity: "High"
---

# Impossible to reveal any drop boxes linked to codes once enough codes have been associated such that `remainingBoxesAmount == 0`

## Description

In `DropBox::associateOneTimeCodeToAddress`, the `boxAmount` linked to allocated codes is deducted from `remainingBoxesAmount` storage:

```solidity
// Decrease the amount of boxes remaining to mint, since they are now associated to be minted
remainingBoxesAmount -= boxAmount;
```

Then in `DropBox::revealDropBoxes` when the user attempts to reveal the boxes previously linked with a code, if all the codes have been previously associated such that `remainingBoxesAmount == 0` the following safety checks cause the transaction to erroneously revert with `NoMoreBoxesToMint` error:

```solidity
// @audit read current `remainingBoxesAmount` from storage
// the box amount linked with this code has already been
// previously deducted in `associateOneTimeCodeToAddress`
uint256 remainingBoxesAmountCache = remainingBoxesAmount;

// @audit since the box amount linked with this code has
// already been deducted from `remainingBoxesAmount`, if
// all codes have been associated, even though not all codes have been
// revealed attempting to reveal any codes will erroneously revert since
// remainingBoxesAmountCache == 0
if (remainingBoxesAmountCache == 0) revert NoMoreBoxesToMint();

// @audit even if the previous check was removed, the transaction would
// still revert here since remainingBoxesAmountCache == 0 but
// oneTimeCodeData.boxAmount > 0
if (remainingBoxesAmountCache < oneTimeCodeData.boxAmount) revert NoMoreBoxesToMint();
```

Once all codes have been associated it is impossible to use any codes to reveal boxes. This makes it impossible to mint the remaining drop boxes linked to the associated but unrevealed codes and hence makes it impossible to claim the `EARNM` tokens associated with them.

## Proof of Concept

Firstly in `test/DropBox/DropBox.t.sol` change the number of boxes such that there is only 1 box:

```diff
    dropBox = new DropBoxMock(
      address(users.operatorOwner),
      "https://api.example.com/",
      "https://api.example.com/contract",
      address(earnmERC20Token),
      address(users.apiAddress),
      [10_000_000, 1_000_000, 100_000, 10_000, 2500, 750],
      [1, 10, 100, 1000, 2000, 6889],
+     [uint16(1), 0, 0, 0, 0, 0],
      ["Mythical Box", "Legendary Box", "Epic Box", "Rare Box", "Uncommon Box", "Common Box"],
      address(vrfHandler)
    );
```

Then add the PoC function to `test/DropBox/behaviors/revealDropBoxes.t.sol`:

```solidity
  function test_revealDropBoxes_ImpossibleToMintLastBox() public {
    string memory code = "validCode";
    uint32 boxAmount = 1;

    _setupAndAllowReveal(code, users.stranger, boxAmount);
    _mockVrfFulfillment(code, users.stranger, boxAmount);
    _validateMinting(dropBox.mock_getMintedTierAmounts(), boxAmount, code);
  }
```

Run the PoC with: `forge test --match-test test_revealDropBoxes_ImpossibleToMintLastBox -vvv`.

The PoC stack trace shows it fails to reveal the last and only box due to `[Revert] NoMoreBoxesToMint()` in `DropBoxMock::revealDropBoxes`.

Commenting out the `remainingBoxesAmountCache` checks in `DropBox::revealDropBoxes` then re-running the PoC shows that the last box can now be revealed.

## Recommendation

Remove the `remainingBoxesAmountCache` checks from `DropBox::revealDropBoxes` since the boxes associated with codes are already deducted inside `DropBox::associateOneTimeCodeToAddress`.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability originates from an incorrect use of the contract state variable that tracks how many drop boxes are still available for minting. When a one‑time code is linked to an address, the function associateOneTimeCodeToAddress deducts the amount of boxes tied to that code from the storage variable remainingBoxesAmount. Later, the revealDropBoxes function reads the same remainingBoxesAmount to decide whether it is allowed to mint the boxes associated with a given code. If all codes have been associated, remainingBoxesAmount becomes zero. The reveal function then checks if remainingBoxesAmountCache == 0 and reverts with the NoMoreBoxesToMint error, even though the specific code still has a positive boxAmount that has never been revealed. Consequently, any user who tries to reveal a box after the last association will see the transaction fail, receive no box, and obtain no EARNM tokens. This situation occurs only after the last code has been associated but before its corresponding box has been revealed, affecting any participant holding such a code and the protocol’s token distribution mechanism. The issue was discovered during a formal audit by Cyfrin, which added a test that associated a single box and then attempted to reveal it, reproducing the revert. The bug is subtle because the remainingBoxesAmount variable correctly reflects the number of boxes left to associate, so the check appears logical; however, it is mistakenly reused as a guard for the reveal step, creating a false‑positive condition that blocks legitimate reveals. From a user’s perspective the UI would show a “Reveal” button that, when pressed, results in a transaction revert and the user receives nothing, contrary to the expectation of receiving a box and its associated tokens. This class of bug can be described as an improper state‑variable reuse leading to an incorrect invariant check, often referred to as a premature depletion guard. The recommended remediation is to remove the remainingBoxesAmountCache checks from revealDropBoxes, allowing the function to rely solely on the per‑code boxAmount to determine mintability, or to redesign the accounting so that the variable is not consulted for reveal eligibility. By fixing the logic, users will be able to reveal boxes even after all codes have been associated, restoring the intended token distribution flow.
