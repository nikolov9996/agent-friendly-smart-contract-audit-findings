---
id: 21796
severity: "High"
---

# `mintToken`

## Description

The `EntropyGenerator` contract has an issue where the `initializeAlphaIndices()` function uses the wrong modifier. This function is supposed to be called by the `TraitForgeNft` contract, but it currently uses the `onlyOwner` modifier instead of `onlyAllowedCaller`.

## Proof of Concept

The function `initializeAlphaIndices()` is intended to be called by the `TraitForgeNft` contract. However, it is currently protected by the `onlyOwner` modifier. This means only the owner of the `EntropyGenerator` contract can call it, not the `TraitForgeNft` contract. The correct modifier should be `onlyAllowedCaller`, which restricts the function to be called by the address set as the `allowedCaller`.

The vulnerability lies in the following line of `EntropyGenerator` contract:

```solidity
function initializeAlphaIndices() public whenNotPaused onlyOwner {
```

The above `initializeAlphaIndices()` is called by `TraitForgeNft._incrementGeneration()`:

```solidity
function _incrementGeneration() private {
  require(
    generationMintCounts[currentGeneration] >= maxTokensPerGen,
    'Generation limit not yet reached'
  );
  currentGeneration++;
  generationMintCounts[currentGeneration] = 0;
  priceIncrement = priceIncrement + priceIncrementByGen;
  entropyGenerator.initializeAlphaIndices();
  emit GenerationIncremented(currentGeneration);
}
```

Some of the important functions defined in `TraitForgeNft` contract, such as `mintToken()`, `mintWithBudget()` and `forge()`, internally use `_incrementGeneration()`. Due to this vulnerability, the execution of these mentioned functions will fail.

## Recommendation

Replace the `onlyOwner` modifier with the `onlyAllowedCaller` modifier in the `initializeAlphaIndices()` function to ensure it can be called by the `TraitForgeNft` contract.

```solidity
- function initializeAlphaIndices() public whenNotPaused onlyOwner {
+ function initializeAlphaIndices() public whenNotPaused onlyAllowedCaller {
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The EntropyGenerator contract contains an incorrect access‑control configuration on the initializeAlphaIndices function. The function is intended to be invoked by the TraitForgeNft contract each time a new generation is created, but it is protected with the onlyOwner modifier instead of the onlyAllowedCaller modifier that restricts calls to the address registered as allowedCaller. Because only the contract owner can satisfy onlyOwner, the TraitForgeNft contract is blocked from executing the call during the _incrementGeneration routine. This blockage causes the generation increment to revert, which in turn makes higher‑level functions such as mintToken, mintWithBudget and forge fail whenever they attempt to advance to a new generation. From a user perspective the transaction simply reverts, the expected token is not minted, and any sent ether is returned, giving the impression that the mint operation does nothing or that funds disappear. The root cause is a classic privilege‑misassignment bug where a developer applied the wrong modifier, violating the business logic that the NFT contract should be the authorized caller. The issue was discovered during a Code4rena audit when the test suite attempted to mint across generations and observed a revert at the generation increment step. It can be hard to notice because the function is public and appears harmless in isolation; the failure only manifests when the specific cross‑contract call is exercised. The vulnerability does not directly enable theft but creates a denial‑of‑service condition that halts the protocol’s core functionality. The recommended remediation is to replace onlyOwner with onlyAllowedCaller on initializeAlphaIndices and ensure the allowedCaller variable is set to the address of the TraitForgeNft contract, thereby restoring the intended call flow and allowing minting operations to succeed.
